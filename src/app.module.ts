import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Result } from 'src/result/entities/result.entity';
import { Market } from 'src/market/entities/market.entity';
import { ResultModule } from 'src/result/result.module';
import { MarketModule } from 'src/market/market.module';
import { ConfigModule } from '@nestjs/config';
import { Product } from 'src/product/entities/product.entity';
import { Material } from 'src/material/entities/material.entity';
import { ProductModule } from 'src/product/product.module';
import { MaterialModule } from 'src/material/material.module';
import { Experience } from 'src/experience/entities/experience.entity';
import { ExperienceModule } from 'src/experience/experience.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    TypeOrmModule.forRoot({
      type: 'postgres',
      host: process.env.POSTGRES_HOST,
      port: parseInt(process.env.POSTGRES_PORT),
      username: process.env.POSTGRES_USER,
      password: `${process.env.POSTGRES_PASSWORD}`,
      database: process.env.POSTGRES_NAME,
      entities: [Product, Material, Result, Market, Experience],
      synchronize: true,
    }),
    ProductModule,
    MaterialModule,
    ResultModule,
    MarketModule,
    ExperienceModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
