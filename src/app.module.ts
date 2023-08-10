import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Item } from 'src/item/entities/item.entity';
import { ItemModule } from 'src/item/item.module';
import { Result } from 'src/result/entities/result.entity';
import { Market } from 'src/market/entities/market.entity';
import { ResultModule } from 'src/result/result.module';
import { MarketModule } from 'src/market/market.module';
import { ConfigModule } from '@nestjs/config';

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
      entities: [Item, Result, Market],
      synchronize: true,
    }),
    ItemModule,
    ResultModule,
    MarketModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
