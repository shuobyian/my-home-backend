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

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      host: process.env.DB_HOST,
      port: parseInt(process.env.DB_PORT),
      username: process.env.DB_USERNAME,
      password: `${process.env.DB_PASSWORD}`,
      database: process.env.DB_NAME,
      entities: [Item, Result, Market],
      synchronize: false,
    }),
    ItemModule,
    ResultModule,
    MarketModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
